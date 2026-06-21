from pathlib import Path

import typer

from smith.cli.console import get_console, print_footer
from smith.core.formatting import format_result_footer
from smith.models.planning_context import PlanningDimension
from smith.services.clarification import generate_questions_from_gaps
from smith.services.context_gap_analysis import parse_dimension_slug
from smith.services.planner import (
    PlanningService,
    format_planning_explain,
    format_planning_readiness,
    format_planning_result,
    get_last_planning_result,
    get_planning_session,
)


def _service(workspace: Path | None) -> PlanningService:
    root = workspace.resolve() if workspace else Path.cwd()
    return PlanningService(cwd=root)


def _parse_answer_pair(raw: str) -> tuple[PlanningDimension, str]:
    if "=" not in raw:
        raise typer.BadParameter(f"Expected dimension=value, got: {raw}")
    key, _, value = raw.partition("=")
    key = key.strip()
    value = value.strip().strip('"').strip("'")
    if not key or not value:
        raise typer.BadParameter(f"Expected dimension=value, got: {raw}")
    dimension = parse_dimension_slug(key)
    if dimension is None:
        valid = ", ".join(d.value for d in PlanningDimension)
        raise typer.BadParameter(f"Unknown dimension '{key}'. Valid: {valid}")
    return dimension, value


def plan_command(
    ctx: typer.Context,
    goal: list[str] = typer.Argument(..., help="Goal to plan for, 'explain', or 'answer'"),
    workspace: Path | None = typer.Option(None, "--workspace", help="Workspace root"),
    prioritize: bool = typer.Option(False, "--prioritize", help="LLM re-rank dimension gaps only"),
    force_plan: bool = typer.Option(
        False, "--force-plan", help="Generate plan even when important gaps remain"
    ),
) -> None:
    """Create a guided plan from cached context.

    Examples:

        smith plan build a drone telemetry platform
        smith plan explain
        smith plan answer timeline="3 months"
    """
    if len(goal) >= 1 and goal[0] == "explain":
        plan_explain(ctx, workspace=workspace)
        return
    if len(goal) >= 2 and goal[0] == "answer":
        plan_answer(ctx, pairs=goal[1:], workspace=workspace)
        return

    goal_text = " ".join(goal)
    console = get_console()
    result = _service(workspace).create_plan(
        goal_text,
        prioritize=prioritize,
        force_plan=force_plan,
    )
    console.print(format_planning_result(result))
    print_footer(format_result_footer("plan", 0))


def plan_answer(
    ctx: typer.Context,
    pairs: list[str] = typer.Argument(..., help="dimension=value answers"),
    workspace: Path | None = typer.Option(None, "--workspace", help="Workspace root"),
) -> None:
    """Record planning answers and refresh gap analysis for the current session.

    Examples:

        smith plan answer timeline="3 months"
        smith plan answer success_criteria="MVP with 100 users"
    """
    session = get_planning_session()
    if session is None or not session.goal:
        raise typer.BadParameter("No active planning session. Run `smith plan <goal>` first.")

    console = get_console()
    service = _service(workspace)
    try:
        for raw in pairs:
            dimension, answer = _parse_answer_pair(raw)
            service.record_decision(dimension, answer)
    except RuntimeError as exc:
        raise typer.BadParameter(str(exc)) from exc

    ctx_obj = service.build_context(session.goal)
    mode, confidence, gaps = service.evaluate_readiness(ctx_obj)
    questions = generate_questions_from_gaps(gaps)

    lines = [
        f"Goal: {session.goal}",
        f"Mode: {mode.replace('_', ' ').title()}",
        f"Confidence: {confidence:.0%}",
        "",
    ]
    if ctx_obj.decisions:
        lines.append("Explicit Decisions:")
        for decision in ctx_obj.decisions:
            label = decision.dimension.value.replace("_", " ").title()
            lines.append(f"- {label}: {decision.answer}")
        lines.append("")
    if gaps:
        lines.append("Remaining Gaps:")
        for gap in gaps[:10]:
            lines.append(f"- {gap.name} ({gap.severity.value})")
        lines.append("")
    if questions:
        lines.append("Questions:")
        for idx, question in enumerate(questions, start=1):
            lines.append(f"{idx}. {question.question}")
        lines.append("")
        lines.append("Next: smith plan answer <dimension>=<value> then smith plan-refresh")
    else:
        lines.append("No remaining questions — run `smith plan-refresh` or re-run `smith plan`.")
    console.print("\n".join(lines))
    print_footer(format_result_footer("plan answer", 0))


def plan_explain(
    ctx: typer.Context,
    workspace: Path | None = typer.Option(None, "--workspace", help="Workspace root"),
) -> None:
    """Show planning provenance for knowns, gaps, and constraints.

    Examples:

        smith plan explain
    """
    console = get_console()
    service = _service(workspace)
    last = get_last_planning_result()
    if last is not None:
        ctx_obj = service.build_context(last.goal)
        console.print(format_planning_explain(ctx_obj, gaps=last.gaps))
    else:
        ctx_obj = service.build_context(None)
        console.print(format_planning_explain(ctx_obj))
    print_footer(format_result_footer("plan explain", 0))


def plan_status(
    ctx: typer.Context,
    workspace: Path | None = typer.Option(None, "--workspace", help="Workspace root"),
) -> None:
    """Display planning readiness without AI calls.

    Examples:

        smith plan-status
    """
    console = get_console()
    readiness = _service(workspace).assess_readiness(None)
    console.print(format_planning_readiness(readiness))
    print_footer(format_result_footer("plan-status", 0))


def plan_refresh(
    ctx: typer.Context,
    workspace: Path | None = typer.Option(None, "--workspace", help="Workspace root"),
    goal: str | None = typer.Option(
        None, "--goal", help="Optional goal for gap analysis"
    ),
) -> None:
    """Rebuild planning context without generating a plan.

    Examples:

        smith plan-refresh
        smith plan-refresh --goal "build a drone platform"
    """
    console = get_console()
    service = _service(workspace)
    session = get_planning_session()
    effective_goal = goal or (session.goal if session else None)
    ctx_obj = service.build_context(effective_goal)
    mode, confidence, gaps = service.evaluate_readiness(ctx_obj)
    console.print(format_planning_explain(ctx_obj, gaps=gaps))
    console.print("")
    console.print(f"Mode: {mode.replace('_', ' ').title()}")
    console.print(f"Confidence: {confidence:.0%}")
    print_footer(format_result_footer("plan-refresh", 0))
