"""Base abstract class for all 24 UPSC Studio specialist agents."""

from __future__ import annotations

import abc
import time
from typing import Any
from upsc_studio.agents.contracts import (
    AgentExecutionContext,
    AgentExecutionResult,
    AgentRole,
    AgentStatus,
    QualityCheckStatus,
)


class BaseSpecialistAgent(abc.ABC):
    """Abstract base class establishing the contract, failure boundaries, and execution for a specialist agent."""

    agent_id: str
    role: AgentRole
    name: str
    description: str
    dependencies: list[str] = []
    is_retry_safe: bool = True
    has_side_effects: bool = False
    max_retries: int = 2

    def run(self, context: AgentExecutionContext) -> AgentExecutionResult:
        """Standard wrapper providing execution timing, exception shielding, and contract validation."""
        t0 = time.perf_counter()
        try:
            # Check upstream dependencies
            for dep_id in self.dependencies:
                dep_res = context.upstream_outputs.get(dep_id)
                if dep_res is None:
                    return AgentExecutionResult(
                        agent_id=self.agent_id,
                        agent_role=self.role,
                        status=AgentStatus.BLOCKED,
                        quality_status=QualityCheckStatus.FAILED,
                        execution_time_sec=round(time.perf_counter() - t0, 3),
                        errors=[f"Required upstream dependency '{dep_id}' is missing from execution context."],
                    )
                if isinstance(dep_res, dict) and dep_res.get("status") in (AgentStatus.FAILED.value, AgentStatus.BLOCKED.value):
                    return AgentExecutionResult(
                        agent_id=self.agent_id,
                        agent_role=self.role,
                        status=AgentStatus.BLOCKED,
                        quality_status=QualityCheckStatus.FAILED,
                        execution_time_sec=round(time.perf_counter() - t0, 3),
                        errors=[f"Required upstream dependency '{dep_id}' failed with status '{dep_res.get('status')}'."],
                    )

            result = self.execute(context)
            result.execution_time_sec = round(time.perf_counter() - t0, 3)
            return result
        except Exception as exc:
            return AgentExecutionResult(
                agent_id=self.agent_id,
                agent_role=self.role,
                status=AgentStatus.FAILED,
                quality_status=QualityCheckStatus.FAILED,
                execution_time_sec=round(time.perf_counter() - t0, 3),
                errors=[f"Unhandled exception in {self.name}: {str(exc)}"],
            )

    @abc.abstractmethod
    def execute(self, context: AgentExecutionContext) -> AgentExecutionResult:
        """Domain-specific logic implemented by each specialist agent."""
        raise NotImplementedError
