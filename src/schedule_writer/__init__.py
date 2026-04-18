"""schedule-writer — builder API and CLI for contingency-dsl schedule strings.

The package emits text in the surface syntax of contingency-dsl (e.g. ``FR 5``,
``Conc(VI 30s, VI 60s)``) without depending on a parser at runtime. Consumers
that want validation can feed the output to ``contingency-dsl-py``.
"""

from schedule_writer.builder import ScheduleBuilder

__all__ = ["ScheduleBuilder"]
