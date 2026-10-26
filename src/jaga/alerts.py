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
    """The verifier's final word on one clip."""
    clip_id: str
    rules_label: str                    # fall_candidate|uncertain|
                                        # negative|no_evidence
    adjudicator_verdict: str | None = None   # fall|benign|uncertain
    adjudicator_usable: bool = False
    pipeline_error: str | None = None


def tier_for(d: Disposition) -> tuple[str, str]:
    """Map a disposition to (tier, reason). Uncertainty escalates."""
    if d.pipeline_error:
        return TIER_CHECK, ("fail-safe: verification unavailable "
                            f"({d.pipeline_error}); a human checks "
                            "rather than the event going silent")
    if d.adjudicator_usable and d.adjudicator_verdict == "fall":
        return TIER_URGENT, "adjudicator confirmed a fall"
    if d.adjudicator_usable and d.adjudicator_verdict == "benign":
        return TIER_NONE, "adjudicator cleared the event as benign"
    if d.rules_label == "fall_candidate":
        return TIER_URGENT, ("rules fall candidate not cleared by "
                             "the adjudicator")
    if d.rules_label in ("uncertain", "no_evidence"):
        return TIER_CHECK, (f"rules outcome {d.rules_label}; "
                            "uncertainty escalates to a human check")
    if d.adjudicator_usable and d.adjudicator_verdict == "uncertain":
        return TIER_CHECK, "adjudicator escalated as uncertain"
    if d.rules_label == "negative":
        return TIER_NONE, "rules negative, no escalation signals"
    return TIER_CHECK, "unclassified disposition; escalating by default"


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
                "state": self.state, "events": self.events}


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
    implemented: bool = False

    def to_dict(self) -> dict:
        return {"status": "designed, not implemented",
                "rooms": self.rooms,
                "active_hours": self.active_hours,
                "recipients": self.recipients,
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
        alert = self._alerts[alert_id]
        if alert.state != "pending":
            raise ValueError(f"alert {alert_id} is {alert.state}")
        alert.state = "acknowledged"
        alert.events.append({"at": self._clock(), "kind": "acknowledged",
                             "by": recipient})
        return alert

    def tick(self, now: float | None = None) -> list[Alert]:
        """Escalate every pending alert past its ack window."""
        now = self._clock() if now is None else now
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
                escalated.append(alert)
        return escalated

    def get(self, alert_id: str) -> Alert:
        return self._alerts[alert_id]
