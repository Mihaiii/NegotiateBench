# -*- coding: utf-8 -*-
"""
Improved haggling agent.

The strategy is based on two ideas:

1. **Dynamic concession schedule** – we start by demanding a
   large share of the total value (≈80 %) and linearly relax the
   requirement to the fair 50 % by the last round.  This gives the
   opponent enough incentive to accept early offers while still
   protecting our own profit.

2. **Very light opponent modelling** – from the opponent's past
   offers we infer which item types they tend to keep (i.e. they
   probably value them highly).  When we build a counter‑offer we
   deliberately leave those items for the opponent, which raises the
   chance that the opponent will accept our proposal.

The code uses only the Python standard library, respects the
5‑second turn limit and follows the required ``Agent`` API.
"""

from __future__ import annotations
from typing import List, Optional


class Agent:
    """
    Negotiation agent.

    Parameters
    ----------
    me : int
        0 if we move first, 1 otherwise (kept for API compatibility).
    counts : list[int]
        Number of objects of each type.
    values : list[int]
        Our per‑item valuation.
    max_rounds : int
        Maximum number of *rounds* (a round = two turns).
    """

    def __init__(self, me: int, counts: List[int],
                 values: List[int], max_rounds: int) -> None:
        self.me = me
        self.total_counts = counts[:]          # never mutated
        self.values = values[:]
        self.max_rounds = max_rounds

        # total value of everything according to us
        self.total_value = sum(c * v for c, v in zip(self.total_counts,
                                                     self.values))

        # we will count how many of our own turns have been played
        self.turns_used = 0                     # each call to offer == one turn

        # store opponent offers to obtain a very cheap estimate of their
        # preferences (how many of each type they tend to keep)
        self.opponent_history: List[List[int]] = []

        # pre‑compute the order of item types by our value (high → low)
        self.value_rank = sorted(
            range(len(self.values)),
            key=lambda i: self.values[i],
            reverse=True,
        )

    # ------------------------------------------------------------------ #
    # Helper utilities
    # ------------------------------------------------------------------ #
    def _value_of_bundle(self, bundle: List[int]) -> int:
        """Return our valuation for a given bundle."""
        return sum(b * v for b, v in zip(bundle, self.values))

    def _current_target(self) -> int:
        """
        Desired minimum value for the current turn.

        Starts around 80 % of the total value and linearly declines
        to 50 % (the fair split) by the final round.
        """
        # how many of *our* turns are left?
        # each round contains two turns, therefore max_turns = 2 * max_rounds
        max_turns = self.max_rounds * 2
        turns_left = max_turns - self.turns_used

        # linear interpolation: 0.80 → 0.50
        fraction = 0.5 + 0.3 * (turns_left / max_turns)   # 0.8 at start, 0.5 at end
        return int(self.total_value * fraction)

    def _estimate_opponent_interest(self) -> List[float]:
        """
        Very cheap estimate: for each type we count how many items the
        opponent has *kept* in the offers we have seen (i.e. total –
        what they gave us).  Normalise to [0, 1].
        """
        if not self.opponent_history:
            return [0.0] * len(self.total_counts)

        kept = [0] * len(self.total_counts)
        for opp_offer in self.opponent_history:
            for i, gave_us in enumerate(opp_offer):
                kept[i] += self.total_counts[i] - gave_us   # items opponent kept

        max_kept = max(kept) if kept else 1
        return [k / max_kept for k in kept]

    def _make_greedy_offer(self, target: int,
                           opp_interest: List[float]) -> List[int]:
        """
        Build a bundle that reaches ``target`` value while trying to
        leave items with high opponent interest for the opponent.
        """
        offer = [0] * len(self.total_counts)
        accumulated = 0

        # we walk through our items ordered by our own value (high → low)
        for idx in self.value_rank:
            if self.values[idx] == 0:
                continue          # never request valueless items

            # remaining items of this type that we could still take
            remaining = self.total_counts[idx] - offer[idx]

            if remaining <= 0:
                continue

            # we would like to keep at least a fraction of this type for the opponent
            # proportional to how much we think they value it.
            # The more they like it, the more we leave for them.
            leave_frac = opp_interest[idx] * 0.5          # up to 50 % of stock
            max_we_can_take = int(remaining * (1 - leave_frac))

            if max_we_can_take <= 0:
                continue

            # how many of this type are needed to reach the target?
            needed = (target - accumulated + self.values[idx] - 1) // self.values[idx]
            take = min(max_we_can_take, needed, remaining)

            if take > 0:
                offer[idx] = take
                accumulated += take * self.values[idx]

            if accumulated >= target:
                break

        # If we couldn't reach the target (e.g., not enough valuable items)
        # just take everything we value positively.
        if accumulated < target:
            for idx in self.value_rank:
                if self.values[idx] > 0:
                    offer[idx] = self.total_counts[idx]

        return offer

    # ------------------------------------------------------------------ #
    # Main interaction method
    # ------------------------------------------------------------------ #
    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        """
        Called each turn.

        Parameters
        ----------
        o : list[int] | None
            The opponent's last offer (expressed as what *we* would receive).
            ``None`` on the very first turn.

        Returns
        -------
        list[int] | None
            ``None`` to accept the opponent's offer,
            otherwise a new offer (what we would like to receive).
        """
        self.turns_used += 1

        # -----------------------------------------------------------------
        # 1)  Evaluate opponent's offer (if any)
        # -----------------------------------------------------------------
        if o is not None:
            # remember it for opponent modelling
            self.opponent_history.append(o)

            our_value = self._value_of_bundle(o)
            target = self._current_target()

            # Accept if the offer meets our current target.
            # In the final round we are even more tolerant: accept any
            # positive value to avoid a walk‑away.
            if our_value >= target or (self.turns_used >= self.max_rounds * 2 and our_value > 0):
                return None

        # -----------------------------------------------------------------
        # 2)  Counter‑offer
        # -----------------------------------------------------------------
        target = self._current_target()
        opp_interest = self._estimate_opponent_interest()
        return self._make_greedy_offer(target, opp_interest)