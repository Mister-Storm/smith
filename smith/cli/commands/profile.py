from pathlib import Path

import typer

from smith.cli.console import get_console, print_footer
from smith.core.formatting import format_result_footer
from smith.services.user_context import (
    UserContextService,
    format_user_profile,
    render_user_context_explain,
    render_user_profile,
)
from smith.services.user_context_store import user_context_path

profile_app = typer.Typer(
    help="User profile and deterministic context (not a memory system)",
    no_args_is_help=True,
)


def _service(workspace: Path | None) -> UserContextService:
    root = workspace.resolve() if workspace else Path.cwd()
    return UserContextService(workspace_root=root)


@profile_app.command("show")
def profile_show(
    ctx: typer.Context,
    workspace: Path | None = typer.Option(None, "--workspace", help="Workspace root for display"),
) -> None:
    """Display the user profile from ~/.smith/user_context.json.

    Examples:

        smith profile show
    """
    profile = _service(workspace).load()
    render_user_profile(profile, get_console())
    print_footer(format_result_footer("profile show", 0))


@profile_app.command("refresh")
def profile_refresh(
    ctx: typer.Context,
    workspace: Path | None = typer.Option(None, "--workspace", help="Workspace to derive from"),
    infer: bool = typer.Option(
        False,
        "--infer",
        help="Enable AI-assisted inference for missing project metadata (optional)",
    ),
) -> None:
    """Rebuild derived profile fields from cached project/workspace context.

    User-defined interests and goals are never overwritten.

    Examples:

        smith profile refresh
        smith profile refresh --workspace ~/development
        smith profile refresh --infer
    """
    service = _service(workspace)
    profile = service.refresh(infer=infer)
    console = get_console()
    render_user_profile(profile, console)
    console.print(f"\nStored at {user_context_path()}")
    print_footer(format_result_footer("profile refresh", 0))


@profile_app.command("set-interest")
def profile_set_interest(
    ctx: typer.Context,
    value: str = typer.Argument(..., help="Interest to add"),
) -> None:
    """Add a user-defined interest.

    Examples:

        smith profile set-interest drones
        smith profile set-interest ai-assistants
    """
    profile = UserContextService().set_interest(value)
    typer.echo(format_user_profile(profile))
    print_footer(format_result_footer("profile set-interest", 0))


@profile_app.command("remove-interest")
def profile_remove_interest(
    ctx: typer.Context,
    value: str = typer.Argument(..., help="Interest to remove"),
) -> None:
    """Remove a user-defined interest."""
    profile = UserContextService().remove_interest(value)
    typer.echo(format_user_profile(profile))
    print_footer(format_result_footer("profile remove-interest", 0))


@profile_app.command("set-goal")
def profile_set_goal(
    ctx: typer.Context,
    value: str = typer.Argument(..., help="Goal to add"),
) -> None:
    """Add a user-defined goal.

    Examples:

        smith profile set-goal build-open-source-ai-assistant
    """
    profile = UserContextService().set_goal(value)
    typer.echo(format_user_profile(profile))
    print_footer(format_result_footer("profile set-goal", 0))


@profile_app.command("remove-goal")
def profile_remove_goal(
    ctx: typer.Context,
    value: str = typer.Argument(..., help="Goal to remove"),
) -> None:
    """Remove a user-defined goal."""
    profile = UserContextService().remove_goal(value)
    typer.echo(format_user_profile(profile))
    print_footer(format_result_footer("profile remove-goal", 0))


@profile_app.command("explain")
def profile_explain(
    ctx: typer.Context,
    workspace: Path | None = typer.Option(None, "--workspace", help="Workspace context scope"),
) -> None:
    """Show how profile fields were derived.

    Examples:

        smith profile explain
    """
    explanation = _service(workspace).explain()
    render_user_context_explain(explanation, get_console())
    print_footer(format_result_footer("profile explain", 0))
