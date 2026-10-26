"""Base Agent Implementation with Autonomous ReAct Loop.

Orchestrates reasoning, tool dispatching via MCP, guardrails enforcement,
HITL approval gates, and observability tracing.
"""

import time
from typing import List, Dict, Any, Optional, Tuple
from agentic_framework.core.llm import llm_client
from agentic_framework.mcp.tools import tool_registry
from agentic_framework.observability.tracer import tracer
from agentic_framework.observability.logger import logger


class BaseAgent:
    """Foundational agent class implementing autonomous ReAct execution loop."""

    def __init__(
        self,
        name: str,
        role: str,
        system_prompt: str,
        allowed_tools: Optional[List[str]] = None,
        max_iterations: int = 8,
    ):
        self.name = name
        self.role = role
        self.system_prompt = system_prompt
        self.allowed_tools = allowed_tools or []
        self.max_iterations = max_iterations

    def get_tool_declarations(self) -> List[Dict[str, Any]]:
        """Filter MCP tools accessible to this agent."""
        all_tools = tool_registry.list_tools()
        if not self.allowed_tools:
            return all_tools
        return [t for t in all_tools if t["name"] in self.allowed_tools]

    def run(self, task_description: str, context: Optional[str] = None) -> Dict[str, Any]:
        """Execute autonomous ReAct loop to solve the assigned task."""
        logger.agent_start(self.name, task_description)
        span_id = tracer.start_span(
            agent_name=self.name,
            task_name=task_description,
            input_data={"context": context, "task": task_description},
        )

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": f"Assigned Task: {task_description}\n\nContext:\n{context or 'No prior context provided.'}",
            },
        ]

        tools = self.get_tool_declarations()
        tool_registry.reset_modification_tracking()
        iteration = 0
        final_answer = ""
        had_tool_errors = False

        try:
            while iteration < self.max_iterations:
                iteration += 1

                # Query LLM with tools
                response = llm_client.chat(messages, tools=tools, span_id=span_id)

                if response.content:
                    logger.thought(self.name, response.content)
                    tracer.record_thought(span_id, response.content)
                    final_answer = response.content

                # Check if model wants to call tools
                if response.has_tool_calls():
                    # Add assistant message with tool calls
                    messages.append({
                        "role": "assistant",
                        "content": response.content,
                        "tool_calls": [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {
                                    "name": tc["name"],
                                    "arguments": str(tc["arguments"]),
                                },
                            }
                            for tc in response.tool_calls
                        ],
                    })

                    # Execute each tool
                    for tc in response.tool_calls:
                        t_name = tc["name"]
                        t_args = tc["arguments"]

                        # Unpack if LLM passed nested {"arguments": ...}
                        if isinstance(t_args, dict) and "arguments" in t_args and len(t_args) == 1:
                            inner = t_args["arguments"]
                            if isinstance(inner, dict):
                                t_args = inner
                            elif isinstance(inner, str):
                                try:
                                    import json, ast
                                    t_args = json.loads(inner) if inner.startswith("{") else ast.literal_eval(inner)
                                except Exception:
                                    pass

                        # Clean concise tool execution log
                        detail = None
                        if isinstance(t_args, dict):
                            detail = t_args.get("file_path") or t_args.get("query") or t_args.get("command") or t_args.get("test_target")
                        logger.tool_call(t_name, str(detail) if detail else None)

                        t_start = time.time()
                        tool_def = tool_registry.get(t_name)
                        if not tool_def:
                            res_str = f"Error: Tool '{t_name}' not found."
                            t_status = "error"
                        else:
                            try:
                                res_str = str(tool_def.func(**t_args))
                                t_status = "success"
                            except Exception as e:
                                res_str = f"Tool execution exception: {e}"
                                t_status = "error"

                        duration_ms = (time.time() - t_start) * 1000.0
                        if t_status == "error":
                            had_tool_errors = True
                            logger.tool_error(t_name, res_str)
                        tracer.record_tool_call(
                            span_id=span_id,
                            tool_name=t_name,
                            args=t_args,
                            result=res_str,
                            duration_ms=round(duration_ms, 2),
                            status=t_status,
                        )

                        # Feed observation back to conversation
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "name": t_name,
                            "content": res_str,
                        })

                else:
                    # Model provided final conclusion without further tool calls
                    break

            modifications = tool_registry.get_recorded_modifications()
            modified_files = [m.file_path for m in modifications]
            total_lines = sum(m.total_lines_changed for m in modifications)
            confidence, risk = self._evaluate_confidence_and_risk(final_answer, modifications, had_tool_errors)

            tracer.end_span(
                span_id=span_id,
                output_data={
                    "final_answer": final_answer,
                    "iterations": iteration,
                    "modified_files": modified_files,
                    "total_lines_changed": total_lines,
                    "confidence_score": confidence,
                    "risk_level": risk,
                },
                status="completed",
            )

            return {
                "agent": self.name,
                "role": self.role,
                "output": final_answer,
                "iterations": iteration,
                "status": "completed",
                "modified_files": modified_files,
                "total_lines_changed": total_lines,
                "confidence_score": confidence,
                "risk_level": risk,
            }

        except Exception as e:
            logger.error(f"Agent {self.name} failed: {e}")
            tracer.end_span(span_id=span_id, status="failed", error_message=str(e))
            return {
                "agent": self.name,
                "role": self.role,
                "output": f"Agent encountered error: {e}",
                "iterations": iteration,
                "status": "failed",
                "modified_files": [],
                "total_lines_changed": 0,
                "confidence_score": 0.0,
                "risk_level": "HIGH",
            }

    def _evaluate_confidence_and_risk(
        self, final_answer: str, modifications: List[Any], had_tool_errors: bool
    ) -> Tuple[float, str]:
        """Infer confidence score and risk level from output and recorded modifications."""
        text_lower = final_answer.lower()

        # 1. Check for explicit confidence in agent output
        import re
        conf_match = re.search(r"confidence[:\s]+([0-9]*\.?[0-9]+)", text_lower)
        if conf_match:
            try:
                val = float(conf_match.group(1))
                if val > 1.0:
                    val = val / 100.0
                risk = "LOW" if val >= 0.85 else ("MEDIUM" if val >= 0.60 else "HIGH")
                return round(val, 2), risk
            except Exception:
                pass

        # 2. Check for explicit uncertainty signals
        if any(w in text_lower for w in ["low confidence", "uncertain", "not confident", "might cause regression", "high risk", "breaking change"]):
            return 0.60, "HIGH"

        if had_tool_errors:
            return 0.50, "HIGH"

        # 3. Assess based on modification footprint
        if not modifications:
            return 1.0, "LOW"

        total_lines = sum(m.total_lines_changed for m in modifications)
        num_files = len(modifications)

        if num_files == 1 and total_lines <= 12:
            return 0.95, "LOW"
        elif num_files == 1 and total_lines <= 30:
            return 0.82, "MEDIUM"
        else:
            return 0.70, "HIGH"
