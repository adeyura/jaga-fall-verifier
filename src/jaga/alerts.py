"""Alert ladder (SPEC D2): tiers, acknowledgement, escalation.

Working software for the response half of Jaga. The verifier's final
disposition for a clip maps to a tier:

- Urgent: a confirmed fall (adjudicator "fall", or a rules
  fall_candidate the adjudicator did not clear).
- Check now: anything uncertain — rules uncertainty, an adjudicator
  that escalated or was unusable, or verification unavailable
  (fail-safe: when the cloud stage cannot answer, a human hears
  about it; silence is never the failure mode).
- No immediate alert: a usable "benign" verdict, or a rules negative.
  Logged, not sent.

An alert walks an ordered recipient list: if the current recipient
does not acknowledge within the ack window, it escalates to the
next. Acknowledgement stops escalation. The ladder is in-memory
with JSON-serializable state; notification transport is out of
scope — dispatches and escalations are recorded as events, which is
what the demo shows.

The consent layer (the watched person chooses rooms, hours,
recipients, retention) is a DESIGN MOCK in this module: the profile
shape exists and is labeled "designed, not implemented", and the
dispatch path deliberately does not consult it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

TIER_URGENT = "urgent"
TIER_CHECK = "check_now"
TIER_NONE = "no_immediate_alert"


@dataclass
class Disposition:
    """The verifier's final word on one clip.

    Producer contract: an adjudication that was ATTEMPTED and failed
    (transport error, unusable output, cloud unavailable) must be
    reported as verification_failed=True (or as pipeline_error when
    the whole segment failed). "The adjudicator never ran" and "the
    adjudicator ran and failed" are different dispositions and must
    never be encoded the same way: the first can be a clean negative,
    the second is a fail-safe escalation. A verdict string is read
    only when adjudicator_usable is True.
    """
    clip_id: str
    rules_label: str                    # fall_candidate|uncertain|
                                        # negative|no_evidence
    adjudicator_verdict: str | None = None   # fall|benign|uncertain
    adjudicator_usable: bool = False
    verification_failed: bool = False
    pipeline_error: str | None = None


_RANK = {TIER_NONE: 0, TIER_CHECK: 1, TIER_URGENT: 2}


def tier_for(d: Disposition) -> tuple[str, str]:
    """Map a disposition to (tier, reason). Uncertainty escalates.

    Monotonic in the failure signals: a pipeline error or a failed
    verification can RAISE a tier to at least Check now, never lower
    one — a confirmed fall stays Urgent even when something else
    also went wrong.
    """
    if d.adjudicator_usable and d.adjudicator_verdict == "fall":
        tier, reason = TIER_URGENT, "adjudicator confirmed a fall"
    elif d.adjudicator_usable and d.adjudicator_verdict == "benign":
        tier, reason = TIER_NONE, "adjudicator cleared the event as benign"
    elif d.rules_label == "fall_candidate":
        tier, reason = TIER_URGENT, ("rules fall candidate not cleared "
                                     "by the adjudicator")
    elif d.adjudicator_usable and d.adjudicator_verdict == "uncertain":
        tier, reason = TIER_CHECK, "adjudicator escalated as uncertain"
    elif d.rules_label in ("uncertain", "no_evidence"):
        tier, reason = TIER_CHECK, (f"rules outcome {d.rules_label}; "
                                    "uncertainty escalates to a human "
                                    "check")
    elif d.rules_label == "negative":
        tier, reason = TIER_NONE, "rules negative, no escalation signals"
    else:
        tier, reason = TIER_CHECK, ("unclassified disposition; "
                                    "escalating by default")
    failure = None
    if d.pipeline_error:
        failure = f"pipeline error: {d.pipeline_error}"
    elif d.verification_failed:
        failure = "cloud verification failed"
    if failure and _RANK[tier] < _RANK[TIER_CHECK]:
        tier = TIER_CHECK
        reason = (f"fail-safe: {failure}; a human checks rather "
                  "than the event going silent")
    elif failure:
        reason = f"{reason} (also: {failure})"
    return tier, reason


@dataclass
class Alert:
    alert_id: str
    clip_id: str
    tier: str
    reason: str
    created_at: float
    recipient_index: int = 0
    state: str = "pending"        # pending|acknowledged|exhausted
    events: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"alert_id": self.alert_id, "clip_id": self.clip_id,
                "tier": self.tier, "reason": self.reason,
                "created_at": self.created_at,
                "recipient_index": self.recipient_index,
                "state": self.state,
                "events": [dict(e) for e in self.events]}


@dataclass
class ConsentProfile:
    """DESIGN MOCK — designed, not implemented (SPEC D2).

    The shape the consent layer will take: the watched person
    chooses the rooms covered, the active hours, who receives
    alerts, and how long anything is retained. Nothing in the
    dispatch path reads this; it exists so the design is reviewable
    and the demo can show it honestly labeled.
    """
    rooms: list[str] = field(default_factory=list)
    active_hours: tuple[int, int] = (0, 24)
    recipients: list[str] = field(default_factory=list)
    retention_days: int = 0

    # A class constant, not a settable field: the mock cannot be
    # flipped to "implemented" by construction.
    implemented = False

    def to_dict(self) -> dict:
        return {"status": "designed, not implemented",
                "rooms": list(self.rooms),
                "active_hours": list(self.active_hours),
                "recipients": list(self.recipients),
                "retention_days": self.retention_days}


class AlertLadder:
    def __init__(self, recipients: list[str], ack_window_s: float = 900.0,
                 clock=time.monotonic):
        if not recipients:
            raise ValueError("the ladder needs at least one recipient")
        if ack_window_s <= 0:
            raise ValueError("ack window must be positive")
        self.recipients = list(recipients)
        self.ack_window_s = float(ack_window_s)
        self._clock = clock
        self._alerts: dict[str, Alert] = {}
        self._seq = 0
        self.log: list[dict] = []       # no-alert dispositions, kept

    def dispatch(self, d: Disposition) -> Alert | None:
        # Exactly one live ladder per clip: a re-dispatch of a clip
        # with a pending alert returns that alert (and records the
        # attempt) instead of notifying every recipient twice.
        for alert in self._alerts.values():
            if alert.clip_id == d.clip_id and alert.state == "pending":
                alert.events.append({
                    "at": self._clock(), "kind": "duplicate_dispatch",
                    "note": "a live alert for this clip already exists"})
                return alert
        tier, reason = tier_for(d)
        if tier == TIER_NONE:
            self.log.append({"clip_id": d.clip_id, "tier": tier,
                             "reason": reason, "at": self._clock()})
            return None
        self._seq += 1
        now = self._clock()
        alert = Alert(alert_id=f"alert-{self._seq}", clip_id=d.clip_id,
                      tier=tier, reason=reason, created_at=now)
        alert.events.append({
            "at": now, "kind": "dispatched",
            "to": self.recipients[0], "tier": tier})
        self._alerts[alert.alert_id] = alert
        return alert

    def acknowledge(self, alert_id: str, recipient: str) -> Alert:
        if alert_id not in self._alerts:
            raise ValueError(f"unknown alert: {alert_id}")
        if recipient not in self.recipients:
            raise ValueError(
                f"{recipient!r} is not a recipient on this ladder")
        alert = self._alerts[alert_id]
        if alert.state == "acknowledged":
            raise ValueError(f"alert {alert_id} is already acknowledged")
        # A late acknowledgement (after exhaustion) is a real event
        # in the world, not an error: record it and close the alert.
        kind = ("late_acknowledged" if alert.state == "exhausted"
                else "acknowledged")
        alert.state = "acknowledged"
        alert.events.append({"at": self._clock(), "kind": kind,
                             "by": recipient})
        return alert

    def tick(self) -> list[Alert]:
        """Escalate every pending alert past its ack window.

        Time comes only from the ladder's injected clock — mixing a
        caller-supplied "now" from another epoch would escalate
        instantly or never. Returns the alerts that escalated to a
        NEXT recipient; an alert that exhausts the ladder is not in
        the return (nobody new was notified) — its state and its
        "exhausted" event are the record, and surfacing it is the
        caller's job.
        """
        now = self._clock()
        escalated = []
        for alert in self._alerts.values():
            if alert.state != "pending":
                continue
            last = alert.events[-1]["at"]
            if now - last < self.ack_window_s:
                continue
            if alert.recipient_index + 1 < len(self.recipients):
                alert.recipient_index += 1
                alert.events.append({
                    "at": now, "kind": "escalated",
                    "to": self.recipients[alert.recipient_index],
                    "reason": "no acknowledgement within the window"})
                escalated.append(alert)
            else:
                alert.state = "exhausted"
                alert.events.append({
                    "at": now, "kind": "exhausted",
                    "reason": "no recipient acknowledged"})
        return escalated

    def get(self, alert_id: str) -> Alert:
        return self._alerts[alert_id]

    def to_dict(self) -> dict:
        return {"recipients": list(self.recipients),
                "ack_window_s": self.ack_window_s,
                "seq": self._seq,
                "log": [dict(x) for x in self.log],
                "alerts": {k: a.to_dict()
                           for k, a in self._alerts.items()}}

    @classmethod
    def from_dict(cls, data: dict, clock=time.monotonic) -> "AlertLadder":
        ladder = cls(data["recipients"],
                     ack_window_s=data["ack_window_s"], clock=clock)
        ladder._seq = data["seq"]
        ladder.log = [dict(x) for x in data["log"]]
        for k, a in data["alerts"].items():
            alert = Alert(alert_id=a["alert_id"], clip_id=a["clip_id"],
                          tier=a["tier"], reason=a["reason"],
                          created_at=a["created_at"],
                          recipient_index=a["recipient_index"],
                          state=a["state"],
                          events=[dict(e) for e in a["events"]])
            ladder._alerts[k] = alert
        return ladder
