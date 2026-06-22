"""Tests for the fusion engine."""

import time

from meetguard.fusion.risk_aggregator import RiskAggregator
from meetguard.fusion.threat_classifier import ThreatClassifier
from meetguard.fusion.alert_rules import AlertRules
from meetguard.utils.models import AlertLevel, DetectorScores


class TestRiskAggregator:
    def test_zero(self):
        agg = RiskAggregator()
        assert agg.aggregate(DetectorScores()) == 0.0

    def test_max(self):
        agg = RiskAggregator()
        scores = DetectorScores(face=1.0, voice=1.0, lip=1.0, nlp=1.0, urgency=1.0)
        assert agg.aggregate(scores) == 1.0

    def test_partial(self):
        agg = RiskAggregator({"face": 1.0, "voice": 0, "lip": 0, "nlp": 0, "urgency": 0})
        assert agg.aggregate(DetectorScores(face=0.5)) == 0.5

    def test_clamps_above_one(self):
        agg = RiskAggregator({"face": 2.0, "voice": 0, "lip": 0, "nlp": 0, "urgency": 0})
        assert agg.aggregate(DetectorScores(face=1.0)) == 1.0

    def test_clamps_below_zero(self):
        agg = RiskAggregator({"face": -1.0, "voice": 0, "lip": 0, "nlp": 0, "urgency": 0})
        assert agg.aggregate(DetectorScores(face=1.0)) == 0.0


class TestThreatClassifier:
    def test_safe(self):
        clf = ThreatClassifier()
        assert clf.classify(0.0) == AlertLevel.SAFE
        assert clf.classify(0.19) == AlertLevel.SAFE

    def test_monitor(self):
        clf = ThreatClassifier()
        assert clf.classify(0.30) == AlertLevel.MONITOR

    def test_suspicious(self):
        clf = ThreatClassifier()
        assert clf.classify(0.50) == AlertLevel.SUSPICIOUS

    def test_critical(self):
        clf = ThreatClassifier()
        assert clf.classify(0.80) == AlertLevel.CRITICAL


class TestAlertRules:
    def test_cooldown(self):
        rules = AlertRules(cooldown_seconds=9999)
        assert rules.should_alert(AlertLevel.CRITICAL, "face")
        assert not rules.should_alert(AlertLevel.CRITICAL, "face")
        assert rules.should_alert(AlertLevel.CRITICAL, "voice")

    def test_noncritical_no_cooldown(self):
        rules = AlertRules(cooldown_seconds=9999)
        assert rules.should_alert(AlertLevel.SUSPICIOUS, "face")
        assert rules.should_alert(AlertLevel.SUSPICIOUS, "face")

    def test_reset(self):
        rules = AlertRules(cooldown_seconds=9999)
        rules.should_alert(AlertLevel.CRITICAL, "face")
        rules.reset()
        assert rules.should_alert(AlertLevel.CRITICAL, "face")
