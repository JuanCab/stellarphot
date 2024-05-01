from ipyautoui import AutoUi

from .models import _extract_short_description

__all__ = ["ui_generator"]


def ui_generator(model):
    """
    Generate a user interface with ipyautoui with a few default settings.

    Parameters
    ----------
    model : `pydantic.BaseModel` subclass
        The model to generate the user interface for.
    """
    ui = AutoUi(model)

    # validation is really messy looking right now, so suppress display of
    # the validation errors. A green check or red x will still be displayed.
    ui.show_validation = False

    # By default nullable are not shown at all but it seems much easier for
    # the user to understand if they are shown but disabled.
    ui.show_null = True

    # In the same spirit, the button to show/hide nullables should be hidden
    # too.
    ui.bn_shownull.layout.display = "none"

    # Set the description to the first sentence of the docstring. The default is
    # to use the entire docstring, which is often too long.
    ui.description = _extract_short_description(model.__doc__)

    # Always show nested models
    ui.open_nested = True

    # Validation is checked every time a value is changed, and the contents of each
    # field are written to the widget if validation passes. In at least one case,
    # the "Observatory" model, this is not helpful because the format of lat/lon is
    # not necessarily what the user entered. Furthermore, you can't edit the value
    # in the widget because it is overwritten every time validation passes. So, for
    # now, we will disable this feature by turning continuous update off for most
    # fields.
    for widget in ui.di_widgets.values():
        if hasattr(widget, "continuous_update"):
            widget.continuous_update = False

    # The save and revert buttons should be enabled only when the user has made a
    # change AND the value in the widget is a valid pydantic model.
    # We begin by disabling the buttons.
    ui.savebuttonbar.bn_save.disabled = True
    ui.savebuttonbar.bn_revert.disabled = True

    # Now we add observers to enable/disable the buttons based on the validity of
    # the value and whether there are unsaved changes.

    # The save button should be enabled only when the user has made a change AND
    # the value in the widget is a valid pydantic model.
    ui.is_valid.observe(
        _handle_save_revert_button_state(ui, ui.savebuttonbar.bn_save), "value"
    )
    ui.savebuttonbar.observe(
        _handle_save_revert_button_state(ui, ui.savebuttonbar.bn_save),
        "unsaved_changes",
    )

    # The revert button should be enabled only when there are unsaved changes.
    ui.savebuttonbar.observe(
        _handle_save_revert_button_state(
            ui, ui.savebuttonbar.bn_revert, must_be_valid=False
        ),
        "unsaved_changes",
    )

    return ui


def _handle_save_revert_button_state(widget, button, must_be_valid=True):
    """
    Return a callback that will enable/disable the save and revert buttons based
    on the validity of the value and whether there are unsaved changes.

    Parameters
    ----------
    widget : `ipyautoui.AutoUi`
        The user interface widget.

    button : `ipywidgets.Button`
        The button to enable/disable based on the widget state.

    must_be_valid : bool, optional
        If `True`, the button will only be enabled if the value in the widget is
        a valid pydantic model. If `False`, the button will be enabled regardless
        of the validity of the value. Default is `True`.
    """

    def handler(_):
        """
        A handler must take an argument but we don't use it here.
        """
        valid_flag = widget.is_valid.value if must_be_valid else True
        needs_to_save = valid_flag and widget.savebuttonbar.unsaved_changes
        button.disabled = not needs_to_save

    return handler
