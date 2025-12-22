# -*- coding: utf-8 -*-
"""
A simple haggling agent.

The agent follows a very light‑weight “good‑enough” strategy:

* It keeps a decreasing acceptance threshold.  In the first turn the
  threshold is 60 % of the total value of all items (according to the
  agent’s own valuation).  After each turn the threshold is lowered
  by a small step (5 % of the total).  This makes the agent more
  willing to accept later offers, which is important because the
  negotiation has a hard deadline (max_rounds).

* When the opponent makes an offer, the agent evaluates the value
  of the bundle it would receive.  If that value meets the current
  threshold the offer is accepted (the method returns ``None``).

* If the offer is not good enough the agent makes a counter‑offer.
  The counter‑offer is built greedily: the agent takes as many items
  as possible from the most valuable type first, then the next most
  valuable type, and so on, until it reaches (or exceeds) the current
  threshold.  Items that have zero value are never requested.

The algorithm uses only the standard library and runs in well under
the 5‑second per‑turn limit.
"""

from __future__ import annotations
from typing import List, Optional


class Agent:
    """
    Negotiation agent.

    Parameters
    ----------
    me : int
        0 if the agent moves first, 1 otherwise (not used by the simple
        strategy but kept for API compatibility).
    counts : list[int]
        Number of objects of each type.
    values : list[int]
        Agent's valuation for a single object of each type.
    max_rounds : int
        Maximum number of *rounds* (a round = two turns).
    """

    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = me
        self.counts = counts[:]          # total stock, never modified
        self.values = values[:]          # agent's per‑item values
        self.max_rounds = max_rounds

        # total value of everything according to us
        self.total_value = sum(c * v for c, v in zip(self.counts, self.values))

        # acceptance threshold starts at 60 % of the total value and will
        # be lowered by 5 % of the total after each turn.
        self.threshold = int(0.60 * self.total_value)
        self.decrement = int(0.05 * self.total_value)

        # how many turns have we already taken (used only to stop the
        # decrement from making the threshold negative)
        self.turns_used = 0

    # --------------------------------------------------------------------- #
    # Helper methods
    # --------------------------------------------------------------------- #
    def _value_of_bundle(self, bundle: List[int]) -> int:
        """Return the agent's value for a given bundle."""
        return sum(b * v for b, v in zip(bundle, self.values))

    def _make_greedy_offer(self) -> List[int]:
        """
        Build a bundle that (approximately) reaches the current threshold.
        The algorithm picks items of highest value first.
        """
        target = self.threshold
        offer = [0] * len(self.counts)

        # indices sorted by value descending
        indices = sorted(range(len(self.values)),
                         key=lambda i: self.values[i],
                         reverse=True)

        # greedy allocation
        accumulated = 0
        for i in indices:
            if self.values[i] == 0:
                continue          # never request valueless items
            max_can_take = self.counts[i] - offer[i]
            if max_can_take == 0:
                continue
            # how many of this type do we need to reach the target?
            needed = (target - accumulated + self.values[i] - 1) // self.values[i]
            take = min(max_can_take, max(0, needed))
            # if we already reached the target, we stop taking more
            if accumulated >= target:
                break
            offer[i] = take
            accumulated += take * self.values[i]

        # If we couldn't reach the threshold (e.g., not enough valuable items),
        # just take everything we value positively.
        if accumulated < target:
            for i in indices:
                if self.values[i] > 0:
                    offer[i] = self.counts[i]

        return offer

    # --------------------------------------------------------------------- #
    # Main interaction method
    # --------------------------------------------------------------------- #
    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        """
        Called each turn.

        Parameters
        ----------
        o : list[int] | None
            The opponent's last offer (expressed as what *we* would receive).
            ``None`` on the very first turn of the negotiation.

        Returns
        -------
        list[int] | None
            ``None`` to accept the opponent's offer,
            otherwise a new offer (what we would like to receive).
        """
        # Decrease the threshold a little – we become more conciliatory
        # as the negotiation proceeds.
        self.threshold = max(0, self.threshold - self.decrement)
        self.turns_used += 1

        # -----------------------------------------------------------------
        # 1) Evaluate opponent's offer (if any)
        # -----------------------------------------------------------------
        if o is not None:
            our_value = self._value_of_bundle(o)
            if our_value >= self.threshold:
                # Accept – returning None tells the framework we accept.
                return None

        # -----------------------------------------------------------------
        # 2) Counter‑offer: try to get at least the current threshold.
        # -----------------------------------------------------------------
        return self._make_greedy_offer()