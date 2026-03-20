"""Prompt Master TUI — The Canvas."""


def launch_tui(idea=None, target=None, resume=None, output=None, model=None, no_api=False):
    """Launch the TUI application."""
    from prompt_master.tui.app import CanvasApp

    app = CanvasApp(
        idea=idea,
        target=target,
        resume=resume,
        output=output,
        model=model,
        no_api=no_api,
    )
    app.run()
